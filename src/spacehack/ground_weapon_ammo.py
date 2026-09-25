"""Ground-weapon magazine and bandolier-reserve engine (doc 19 phase 3;
bandolier store swap doc 52 phase 1).

Pure magazine decrements, reserve counting, and the transactional
reload moved here when ground_equipment hit the architecture ratchet
(doc 51 phase 3 build); ground_equipment re-exports the surface so
every caller import stays stable. The reserve store is the bandolier
dict (``ammo_type`` → rounds) since doc 52 — pack stacks are legacy
records, migrated into the bandolier on load.
"""

from __future__ import annotations

from .data.ground_weapons import find_ground_weapon
from .ground_equipment import GroundWeaponInstance


def consume_weapon_round(instance: GroundWeaponInstance) -> GroundWeaponInstance:
    """Return the instance after one shot, decrementing its loaded ammo."""
    if instance.loaded_ammo is None:
        return instance
    spec = find_ground_weapon(instance.weapon_id)
    return GroundWeaponInstance(
        instance.weapon_id, max(0, instance.loaded_ammo - spec.ammo_per_shot),
        instance.quality,
    )


def magazine_indicator(spec, instance) -> str:
    """The ``[loaded/cap]`` magazine suffix for reloadable weapons.

    One formatter for the C screen's member rows and the dungeon HUD's
    weapon rows (doc 52.3); capacity is the catalog value the reload
    engine fills to.
    """
    if spec.ammo_capacity <= 0:
        return ""
    loaded = instance.loaded_ammo if instance.loaded_ammo is not None else 0
    return f" [{loaded}/{spec.ammo_capacity}]"


def reload_amount(loaded: int, capacity: int, reserve: int) -> int:
    """Rounds that move from reserve into the magazine (0 if none needed)."""
    return min(max(0, capacity - loaded), reserve)


def reserve_ammo_count(bandolier: dict[str, int], ammo_type: str) -> int:
    """Reserve rounds carried for ``ammo_type`` in the bandolier."""
    return bandolier.get(ammo_type, 0)


def _apply_reload_at(
    equipped_weapons: list[GroundWeaponInstance],
    slot_index: int,
    bandolier: dict[str, int],
) -> GroundWeaponInstance:
    """Reload the weapon at ``slot_index`` from the bandolier; transactional."""
    instance = equipped_weapons[slot_index]
    spec = find_ground_weapon(instance.weapon_id)
    if spec.ammo_capacity <= 0 or spec.ammo_type is None:
        raise ValueError("That weapon cannot be reloaded")
    loaded = instance.loaded_ammo if instance.loaded_ammo is not None else 0
    if loaded >= spec.ammo_capacity:
        raise ValueError("Magazine is already full")
    reserve = bandolier.get(spec.ammo_type, 0)
    amount = reload_amount(loaded, spec.ammo_capacity, reserve)
    if amount <= 0:
        raise ValueError(f"No {spec.ammo_type} ammo in storage")
    bandolier[spec.ammo_type] = reserve - amount
    new_instance = GroundWeaponInstance(
        instance.weapon_id, loaded + amount, instance.quality,
    )
    equipped_weapons[slot_index] = new_instance
    return new_instance


def apply_reload(
    equipped_weapons: list[GroundWeaponInstance],
    slot_index: int,
    bandolier: dict[str, int],
) -> GroundWeaponInstance:
    """Reload one active weapon from the bandolier transactionally."""
    if not 0 <= slot_index < len(equipped_weapons):
        raise IndexError("Invalid ground weapon slot")
    return _apply_reload_at(equipped_weapons, slot_index, bandolier)


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
