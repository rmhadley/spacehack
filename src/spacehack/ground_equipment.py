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
from .data.ground_weapons import find_ground_weapon


ARMORY_STORAGE = "armory"
EXPEDITION_INVENTORY = "expedition"
BASE_EXPEDITION_SLOTS = 4
WEAPON_SLOT_COUNT = 2


@dataclass(frozen=True)
class StoredGroundEquipment:
    """One owned ground weapon or armor item."""

    item_type: str
    item_id: str


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
    """Install a stored weapon, atomically preserving displaced weapons.

    A one-handed weapon installs without displacement when the current
    logical occupancy has room. A two-handed weapon, or a weapon installed
    into a full loadout, replaces the current active weapons and requires an
    explicit destination for every displaced item.
    """
    _require_container(container)
    if not 0 <= storage_index < len(storage):
        raise IndexError("Invalid stored ground equipment index")
    selected = storage[storage_index]
    _validate_entry(selected)
    if selected.item_type != "weapon":
        raise ValueError("Stored item is not a weapon")
    current = list(equipped_weapons)
    fits_without_replacement = can_fit_weapons(current, selected.item_id)
    displaced = [] if fits_without_replacement else [
        StoredGroundEquipment("weapon", weapon_id) for weapon_id in current
    ]
    if displaced_storage is None and displaced:
        raise ValueError("A destination is required for displaced weapons")
    if displaced and displaced_container is None:
        raise ValueError("A destination container is required for displaced weapons")
    target_storage = displaced_storage if displaced_storage is not None else []
    proposed_target = [*target_storage, *displaced]
    _validate_transfer_capacity(
        storage, target_storage, len(displaced),
        destination_container=displaced_container or container,
        strength=strength,
    )
    validate_storage(proposed_target)
    _apply_weapon_install(
        equipped_weapons, storage, storage_index, selected.item_id,
        displaced_storage, displaced, fits_without_replacement,
    )
    return selected


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
    slot = find_ground_armor(selected.item_id).slot
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
    proposed_target = [*target_storage, *displaced]
    _validate_transfer_capacity(
        storage, target_storage, len(displaced),
        destination_container=displaced_container or container,
        strength=strength,
    )
    validate_storage(proposed_target)
    storage.pop(storage_index)
    if displaced_storage is not None:
        displaced_storage.extend(displaced)
    equipped_armor[slot] = selected.item_id
    return selected


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
