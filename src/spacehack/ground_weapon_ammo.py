"""Ground-weapon magazine and reserve-ammo engine (doc 19 phase 3).

Pure magazine decrements, reserve counting, and the transactional
reload moved here when ground_equipment hit the architecture ratchet
(doc 51 phase 3 build); ground_equipment re-exports the surface so
every caller import stays stable.
"""

from __future__ import annotations

from .data.ground_items import find_ground_ammo
from .data.ground_weapons import find_ground_weapon
from .ground_equipment import GroundItemStack, GroundWeaponInstance


def consume_weapon_round(instance: GroundWeaponInstance) -> GroundWeaponInstance:
    """Return the instance after one shot, decrementing its loaded ammo."""
    if instance.loaded_ammo is None:
        return instance
    spec = find_ground_weapon(instance.weapon_id)
    return GroundWeaponInstance(
        instance.weapon_id, max(0, instance.loaded_ammo - spec.ammo_per_shot),
        instance.quality,
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
    new_instance = GroundWeaponInstance(
        instance.weapon_id, loaded + amount, instance.quality,
    )
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
