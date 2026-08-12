"""Phase 1 tests for ground equipment ownership and mutation."""

from __future__ import annotations

import pytest

from src.spacehack.ground_equipment import (
    ARMORY_STORAGE,
    EXPEDITION_INVENTORY,
    add_stored,
    remove_armor,
    remove_weapon,
    StoredGroundEquipment,
    can_fit_weapons,
    displaced_weapon_count,
    expedition_capacity,
    preferred_displacement_container,
    install_armor,
    install_weapon,
    sell_stored,
    store_armor,
    store_weapon,
    transfer_item,
)


def test_expedition_capacity_uses_strength_bonus():
    assert expedition_capacity(9) == 4
    assert expedition_capacity(10) == 4
    assert expedition_capacity(19) == 4
    assert expedition_capacity(20) == 5
    assert expedition_capacity(40) == 7


def test_displacement_prefers_pack_then_falls_back_to_armory():
    assert displaced_weapon_count(["laser_pistol", "kinetic_pistol"], "laser_rifle") == 2
    assert preferred_displacement_container(1, 4, 2, ARMORY_STORAGE) == EXPEDITION_INVENTORY
    assert preferred_displacement_container(3, 4, 2, ARMORY_STORAGE) == ARMORY_STORAGE
    assert preferred_displacement_container(4, 4, 1, EXPEDITION_INVENTORY) == EXPEDITION_INVENTORY


def test_two_handed_fit_uses_logical_slot_occupancy():
    assert can_fit_weapons([], "laser_rifle")
    assert can_fit_weapons(["laser_pistol"], "kinetic_pistol")
    assert not can_fit_weapons(["laser_pistol", "kinetic_pistol"], "laser_rifle")
    assert not can_fit_weapons(["laser_rifle"], "combat_knife")


def test_store_weapon_is_atomic_when_expedition_pack_is_full():
    equipped = ["laser_pistol"]
    storage = [
        StoredGroundEquipment("armor", "light_helmet"),
        StoredGroundEquipment("armor", "light_vest"),
        StoredGroundEquipment("armor", "combat_boots"),
        StoredGroundEquipment("weapon", "combat_knife"),
    ]
    original = list(storage)
    with pytest.raises(ValueError, match="full"):
        store_weapon(
            equipped, storage, 0,
            container=EXPEDITION_INVENTORY, strength=10,
        )
    assert equipped == ["laser_pistol"]
    assert storage == original


def test_store_armor_moves_one_item_and_preserves_duplicates():
    equipped = {"body": "light_vest"}
    storage = [StoredGroundEquipment("armor", "light_vest")]
    entry = store_armor(equipped, storage, "body")
    assert entry == StoredGroundEquipment("armor", "light_vest")
    assert equipped == {}
    assert storage == [
        StoredGroundEquipment("armor", "light_vest"),
        StoredGroundEquipment("armor", "light_vest"),
    ]


def test_install_one_handed_weapon_into_free_slot():
    equipped = ["laser_pistol"]
    storage = [StoredGroundEquipment("weapon", "combat_knife")]
    selected = install_weapon(equipped, storage, 0)
    assert selected.item_id == "combat_knife"
    assert equipped == ["laser_pistol", "combat_knife"]
    assert storage == []


def test_install_two_handed_weapon_atomically_displaces_both_weapons():
    equipped = ["laser_pistol", "kinetic_pistol"]
    storage = [StoredGroundEquipment("weapon", "laser_rifle")]
    displaced = []
    selected = install_weapon(
        equipped, storage, 0,
        displaced_storage=displaced,
        container=ARMORY_STORAGE,
        displaced_container=ARMORY_STORAGE,
    )
    assert selected.item_id == "laser_rifle"
    assert equipped == ["laser_rifle"]
    assert storage == []
    assert displaced == [
        StoredGroundEquipment("weapon", "laser_pistol"),
        StoredGroundEquipment("weapon", "kinetic_pistol"),
    ]


def test_two_handed_install_without_destination_leaves_state_unchanged():
    equipped = ["laser_pistol", "kinetic_pistol"]
    storage = [StoredGroundEquipment("weapon", "laser_rifle")]
    with pytest.raises(ValueError, match="destination"):
        install_weapon(equipped, storage, 0)
    assert equipped == ["laser_pistol", "kinetic_pistol"]
    assert storage == [StoredGroundEquipment("weapon", "laser_rifle")]


def test_install_armor_replaces_same_slot_into_destination():
    equipped = {"body": "light_vest"}
    storage = [StoredGroundEquipment("armor", "heavy_vest")]
    displaced = []
    install_armor(
        equipped, storage, 0,
        displaced_storage=displaced,
        displaced_container=ARMORY_STORAGE,
    )
    assert equipped == {"body": "heavy_vest"}
    assert storage == []
    assert displaced == [StoredGroundEquipment("armor", "light_vest")]


def test_displacement_requires_explicit_destination_container():
    equipped = ["laser_pistol", "kinetic_pistol"]
    storage = [StoredGroundEquipment("weapon", "laser_rifle")]
    displaced = []
    with pytest.raises(ValueError, match="destination container"):
        install_weapon(
            equipped, storage, 0,
            displaced_storage=displaced,
            container=ARMORY_STORAGE,
        )
    assert equipped == ["laser_pistol", "kinetic_pistol"]
    assert storage == [StoredGroundEquipment("weapon", "laser_rifle")]
    assert displaced == []


def test_armory_to_expedition_displacement_rejects_full_pack_atomically():
    equipped = ["laser_pistol", "kinetic_pistol"]
    storage = [StoredGroundEquipment("weapon", "laser_rifle")]
    pack = [
        StoredGroundEquipment("armor", "light_helmet"),
        StoredGroundEquipment("armor", "light_vest"),
        StoredGroundEquipment("armor", "combat_boots"),
    ]
    original_pack = list(pack)
    with pytest.raises(ValueError, match="full"):
        install_weapon(
            equipped, storage, 0,
            displaced_storage=pack,
            container=ARMORY_STORAGE,
            displaced_container=EXPEDITION_INVENTORY,
            strength=10,
        )
    assert equipped == ["laser_pistol", "kinetic_pistol"]
    assert storage == [StoredGroundEquipment("weapon", "laser_rifle")]
    assert pack == original_pack


def test_expedition_to_expedition_replacement_keeps_pack_capacity():
    equipped = ["laser_pistol", "kinetic_pistol"]
    pack = [
        StoredGroundEquipment("weapon", "laser_rifle"),
        StoredGroundEquipment("armor", "light_helmet"),
        StoredGroundEquipment("armor", "light_vest"),
    ]
    install_weapon(
        equipped, pack, 0,
        displaced_storage=pack,
        container=EXPEDITION_INVENTORY,
        displaced_container=EXPEDITION_INVENTORY,
        strength=10,
    )
    assert equipped == ["laser_rifle"]
    assert pack == [
        StoredGroundEquipment("armor", "light_helmet"),
        StoredGroundEquipment("armor", "light_vest"),
        StoredGroundEquipment("weapon", "laser_pistol"),
        StoredGroundEquipment("weapon", "kinetic_pistol"),
    ]


def test_transfer_item_respects_expedition_capacity_without_partial_mutation():
    source = [StoredGroundEquipment("weapon", "combat_knife")]
    destination = [
        StoredGroundEquipment("armor", "light_helmet"),
        StoredGroundEquipment("armor", "light_vest"),
        StoredGroundEquipment("armor", "combat_boots"),
        StoredGroundEquipment("armor", "tactical_gloves"),
    ]
    with pytest.raises(ValueError, match="full"):
        transfer_item(
            source, destination, 0,
            destination_container=EXPEDITION_INVENTORY, strength=10,
        )
    assert source == [StoredGroundEquipment("weapon", "combat_knife")]
    assert len(destination) == 4


def test_add_stored_validates_and_appends_to_selected_container():
    storage = []
    entry = StoredGroundEquipment("weapon", "laser_pistol")

    assert add_stored(
        storage, entry,
        container=ARMORY_STORAGE,
    ) == entry
    assert storage == [entry]


def test_add_stored_rejects_full_expedition_pack_atomically():
    storage = [
        StoredGroundEquipment("armor", "light_helmet"),
        StoredGroundEquipment("armor", "light_vest"),
        StoredGroundEquipment("armor", "combat_boots"),
        StoredGroundEquipment("weapon", "combat_knife"),
    ]
    original = list(storage)

    with pytest.raises(ValueError, match="full"):
        add_stored(
            storage,
            StoredGroundEquipment("weapon", "laser_pistol"),
            container=EXPEDITION_INVENTORY,
            strength=10,
        )

    assert storage == original


def test_remove_active_ground_equipment_returns_owned_entry():
    weapons = ["laser_pistol", "combat_knife"]
    armor = {"body": "light_vest"}

    assert remove_weapon(weapons, 0) == StoredGroundEquipment("weapon", "laser_pistol")
    assert remove_armor(armor, "body") == StoredGroundEquipment("armor", "light_vest")
    assert weapons == ["combat_knife"]
    assert armor == {}


def test_sell_stored_removes_exactly_one_duplicate():
    storage = [
        StoredGroundEquipment("weapon", "combat_knife"),
        StoredGroundEquipment("weapon", "combat_knife"),
    ]
    assert sell_stored(storage, 1) == StoredGroundEquipment("weapon", "combat_knife")
    assert storage == [StoredGroundEquipment("weapon", "combat_knife")]
