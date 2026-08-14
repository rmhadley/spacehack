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


def expedition_capacity(strength: int) -> int:
    """Return reserve-item capacity for a character's Strength."""
    return BASE_EXPEDITION_SLOTS + max(0, (strength - 10) // 10)


def weapon_hands(weapon_id: str) -> int:
    """Return the logical weapon-slot occupancy for a catalog weapon."""
    return find_ground_weapon(weapon_id).hands


def weapon_slot_occupancy(weapon_ids: Iterable[str]) -> int:
    """Return logical hand occupancy for an active weapon list."""
    return sum(weapon_hands(weapon_id) for weapon_id in weapon_ids)


def can_fit_weapons(weapon_ids: Iterable[str], new_weapon_id: str) -> bool:
    """Return whether a weapon can fit without replacing active weapons."""
    return weapon_slot_occupancy(weapon_ids) + weapon_hands(new_weapon_id) <= WEAPON_SLOT_COUNT


def displaced_weapon_count(
    weapon_ids: Iterable[str], new_weapon_id: str,
) -> int:
    """Return how many active weapons an equip action must displace."""
    current = tuple(weapon_ids)
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
    equipped_weapons: list[str],
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
    if fits_without_replacement:
        equipped_weapons.append(weapon_id)
    else:
        equipped_weapons[:] = [weapon_id]


def store_weapon(
    equipped_weapons: list[str],
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
    weapon_id = equipped_weapons[slot_index]
    entry = StoredGroundEquipment("weapon", weapon_id)
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
    equipped_weapons: list[str],
    slot_index: int,
) -> StoredGroundEquipment:
    """Remove one active weapon and return its owned-equipment entry."""
    if not 0 <= slot_index < len(equipped_weapons):
        raise IndexError("Invalid ground weapon slot")
    entry = StoredGroundEquipment("weapon", equipped_weapons[slot_index])
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
    equipped_weapons: list[str],
    slot_index: int,
    weapon_id: str,
) -> list[StoredGroundEquipment]:
    """Return the active weapons displaced by a slot-targeted swap."""
    current = list(equipped_weapons)
    selected_hands = weapon_hands(weapon_id)
    if selected_hands == 2:
        return [StoredGroundEquipment("weapon", item_id) for item_id in current]
    if len(current) == 1 and weapon_hands(current[0]) == 2:
        return [StoredGroundEquipment("weapon", current[0])]
    if slot_index < len(current):
        return [StoredGroundEquipment("weapon", current[slot_index])]
    return []


def swap_weapon_from_expedition(
    equipped_weapons: list[str],
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
    equipped_weapons: list[str],
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
    if slot_index == 1 and equipped_weapons and weapon_hands(equipped_weapons[0]) == 2:
        raise ValueError("Weapon 2 is occupied by a two-handed weapon")
    return selected


def _set_swapped_weapon(
    equipped_weapons: list[str],
    slot_index: int,
    selected: StoredGroundEquipment,
) -> None:
    """Install a swapped-in weapon into the requested active slot."""
    selected_hands = weapon_hands(selected.item_id)
    if selected_hands == 2:
        equipped_weapons[:] = [selected.item_id]
    elif len(equipped_weapons) == 1 and weapon_hands(equipped_weapons[0]) == 2:
        equipped_weapons[:] = [selected.item_id]
    elif slot_index < len(equipped_weapons):
        equipped_weapons[slot_index] = selected.item_id
    else:
        equipped_weapons.append(selected.item_id)


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
    equipped_weapons: list[str],
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
    equipped_weapons: list[str],
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
        StoredGroundEquipment("weapon", w) for w in current
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
) -> StoredGroundEquipment:
    """Move one stored item between containers without partial mutation."""
    _require_container(destination_container)
    if not 0 <= index < len(source):
        raise IndexError("Invalid stored ground equipment index")
    entry = source[index]
    _validate_entry(entry)
    proposed = [*destination, entry]
    if destination_container == EXPEDITION_INVENTORY:
        _require_expedition_capacity(proposed, strength)
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


def _merge_item_stack(items, index: int, stack: GroundItemStack) -> GroundItemStack:
    """Merge ``stack`` into the existing stack at ``index`` in place."""
    existing = items[index]
    capacity = item_stack_capacity(stack.item_type, stack.item_id)
    merged = GroundItemStack(
        stack.item_type, stack.item_id,
        min(existing.quantity + stack.quantity, capacity),
    )
    items[index] = merged
    return merged


def add_item_stack(
    equipment,
    items,
    stack: GroundItemStack,
    *,
    strength: int,
) -> GroundItemStack:
    """Add or merge one field-item stack into the Expedition Pack.

    Transactional: validation and capacity checks happen before any
    mutation. Merging into an existing partial stack consumes no slot;
    a new stack consumes one.
    """
    validate_item_stack(stack)
    merge_index = item_stack_merge_index(items, stack)
    if merge_index is not None:
        return _merge_item_stack(items, merge_index, stack)
    if expedition_slot_count(equipment, items) + 1 > expedition_capacity(strength):
        raise ValueError("Expedition inventory is full")
    items.append(stack)
    return stack
