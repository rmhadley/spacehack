"""Phase 1 tests for ground equipment ownership and mutation."""

from __future__ import annotations

import pytest

from src.spacehack import loot
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
    sum_armor_bonus,
    store_armor,
    store_weapon,
    swap_armor_from_expedition,
    swap_weapon_from_expedition,
    tier_filtered_equipment,
    transfer_item,
    GroundWeaponInstance,
    parse_weapon_instance,
    weapon_ids,
    weapon_instance,
)


def test_expedition_capacity_uses_strength_bonus():
    assert expedition_capacity(9) == 4
    assert expedition_capacity(10) == 4
    assert expedition_capacity(19) == 4
    assert expedition_capacity(20) == 5
    assert expedition_capacity(40) == 7


def test_sum_armor_bonus_totals_a_single_field_across_armor():
    assert sum_armor_bonus(["cybernetic_legs", "cybernetic_eyes"], "ap_bonus") == 1
    assert sum_armor_bonus(["cybernetic_eyes"], "hit_bonus") == 8
    assert sum_armor_bonus(["cybernetic_torso"], "hp_bonus") == 3


def test_sum_armor_bonus_skips_empty_and_unknown_ids():
    assert sum_armor_bonus([None, "missing_id", "cybernetic_arms"], "melee_bonus") == 2
    assert sum_armor_bonus([], "ap_bonus") == 0


def test_sum_armor_bonus_rejects_unknown_field():
    with pytest.raises(ValueError):
        sum_armor_bonus(["cybernetic_legs"], "defense")


def test_tier_filtered_equipment_drops_items_above_tier():
    pool = (("weapon", "survival_axe"), ("weapon", "railgun"), ("armor", "mag_boots"))
    assert tier_filtered_equipment(pool, 1) == (("weapon", "survival_axe"),)


def test_tier_filtered_equipment_keeps_at_or_below_tier():
    pool = (("armor", "heavy_vest"), ("weapon", "plasma_pistol"))
    assert tier_filtered_equipment(pool, 3) == (
        ("armor", "heavy_vest"),
        ("weapon", "plasma_pistol"),
    )


def test_tier_filtered_equipment_skips_unknown_ids():
    pool = (("weapon", "missing_id"), ("weapon", "combat_knife"))
    assert tier_filtered_equipment(pool, 1) == (("weapon", "combat_knife"),)


def test_displacement_prefers_pack_then_falls_back_to_armory():
    assert displaced_weapon_count(
        [weapon_instance("laser_pistol"), weapon_instance("kinetic_pistol")],
        "laser_rifle",
    ) == 2
    assert preferred_displacement_container(1, 4, 2, ARMORY_STORAGE) == EXPEDITION_INVENTORY
    assert preferred_displacement_container(3, 4, 2, ARMORY_STORAGE) == ARMORY_STORAGE
    assert preferred_displacement_container(4, 4, 1, EXPEDITION_INVENTORY) == EXPEDITION_INVENTORY


def test_two_handed_fit_uses_logical_slot_occupancy():
    assert can_fit_weapons([], "laser_rifle")
    assert can_fit_weapons([weapon_instance("laser_pistol")], "kinetic_pistol")
    assert not can_fit_weapons(
        [weapon_instance("laser_pistol"), weapon_instance("kinetic_pistol")],
        "laser_rifle",
    )
    assert not can_fit_weapons([weapon_instance("laser_rifle")], "combat_knife")


def test_store_weapon_is_atomic_when_expedition_pack_is_full():
    equipped = [weapon_instance("laser_pistol")]
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
    assert equipped == [weapon_instance("laser_pistol")]
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
    equipped = [weapon_instance("laser_pistol")]
    storage = [StoredGroundEquipment("weapon", "combat_knife")]
    selected = install_weapon(equipped, storage, 0)
    assert selected.item_id == "combat_knife"
    assert equipped == [weapon_instance("laser_pistol"), weapon_instance("combat_knife")]
    assert storage == []


def test_install_two_handed_weapon_atomically_displaces_both_weapons():
    equipped = [weapon_instance("laser_pistol"), weapon_instance("kinetic_pistol")]
    storage = [StoredGroundEquipment("weapon", "laser_rifle")]
    displaced = []
    selected = install_weapon(
        equipped, storage, 0,
        displaced_storage=displaced,
        container=ARMORY_STORAGE,
        displaced_container=ARMORY_STORAGE,
    )
    assert selected.item_id == "laser_rifle"
    assert equipped == [weapon_instance("laser_rifle")]
    assert storage == []
    assert displaced == [
        StoredGroundEquipment("weapon", "laser_pistol"),
        StoredGroundEquipment("weapon", "kinetic_pistol"),
    ]


def test_two_handed_install_without_destination_leaves_state_unchanged():
    equipped = [weapon_instance("laser_pistol"), weapon_instance("kinetic_pistol")]
    storage = [StoredGroundEquipment("weapon", "laser_rifle")]
    with pytest.raises(ValueError, match="destination"):
        install_weapon(equipped, storage, 0)
    assert equipped == [weapon_instance("laser_pistol"), weapon_instance("kinetic_pistol")]
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
    equipped = [weapon_instance("laser_pistol"), weapon_instance("kinetic_pistol")]
    storage = [StoredGroundEquipment("weapon", "laser_rifle")]
    displaced = []
    with pytest.raises(ValueError, match="destination container"):
        install_weapon(
            equipped, storage, 0,
            displaced_storage=displaced,
            container=ARMORY_STORAGE,
        )
    assert equipped == [weapon_instance("laser_pistol"), weapon_instance("kinetic_pistol")]
    assert storage == [StoredGroundEquipment("weapon", "laser_rifle")]
    assert displaced == []


def test_armory_to_expedition_displacement_rejects_full_pack_atomically():
    equipped = [weapon_instance("laser_pistol"), weapon_instance("kinetic_pistol")]
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
    assert equipped == [weapon_instance("laser_pistol"), weapon_instance("kinetic_pistol")]
    assert storage == [StoredGroundEquipment("weapon", "laser_rifle")]
    assert pack == original_pack


def test_expedition_to_expedition_replacement_keeps_pack_capacity():
    equipped = [weapon_instance("laser_pistol"), weapon_instance("kinetic_pistol")]
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
    assert equipped == [weapon_instance("laser_rifle")]
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
    weapons = [weapon_instance("laser_pistol"), weapon_instance("combat_knife")]
    armor = {"body": "light_vest"}

    assert remove_weapon(weapons, 0) == StoredGroundEquipment("weapon", "laser_pistol")
    assert remove_armor(armor, "body") == StoredGroundEquipment("armor", "light_vest")
    assert weapons == [weapon_instance("combat_knife")]
    assert armor == {}


def test_swap_two_handed_weapon_cannot_target_weapon_two():
    equipped = [weapon_instance("laser_pistol")]
    pack = [StoredGroundEquipment("weapon", "laser_rifle")]

    with pytest.raises(ValueError, match="Weapon 1"):
        swap_weapon_from_expedition(equipped, pack, 0, 1)

    assert equipped == [weapon_instance("laser_pistol")]
    assert pack == [StoredGroundEquipment("weapon", "laser_rifle")]


def test_swap_weapon_from_expedition_replaces_requested_slot():
    equipped = [weapon_instance("laser_pistol"), weapon_instance("combat_knife")]
    pack = [StoredGroundEquipment("weapon", "stun_baton")]

    trade_result = swap_weapon_from_expedition(
        equipped, pack, 0, 1, strength=10,
    )

    assert trade_result.item_id == "stun_baton"
    assert equipped == [weapon_instance("laser_pistol"), weapon_instance("stun_baton")]
    assert pack == [StoredGroundEquipment("weapon", "combat_knife")]


def test_equipment_loot_pickup_adds_to_pack_and_removes_entity():
    entity = type("Loot", (), {
        "loot_data": {"item_type": "weapon", "item_id": "combat_knife"},
    })()
    ctx = type("Context", (), {
        "ground_stats": type("Stats", (), {"strength": 10})(),
        "ground_expedition_inventory": [],
        "game_map": type("Map", (), {"entities": [entity]})(),
        "log": type("Log", (), {"add": lambda self, _message: None})(),
    })()

    assert loot._apply_equipment_loot_pickup(ctx, entity)
    assert ctx.ground_expedition_inventory == [
        StoredGroundEquipment("weapon", "combat_knife"),
    ]
    assert entity not in ctx.game_map.entities


def test_full_expedition_pack_leaves_equipment_loot_on_floor(monkeypatch):
    entity = type("Loot", (), {
        "loot_data": {"item_type": "armor", "item_id": "heavy_vest"},
    })()
    pack = [
        StoredGroundEquipment("armor", "light_helmet"),
        StoredGroundEquipment("armor", "light_vest"),
        StoredGroundEquipment("armor", "combat_boots"),
        StoredGroundEquipment("weapon", "combat_knife"),
    ]
    messages = []
    ctx = type("Context", (), {
        "ground_stats": type("Stats", (), {"strength": 10})(),
        "ground_expedition_inventory": pack,
        "game_map": type("Map", (), {"entities": [entity]})(),
        "log": type("Log", (), {"add": lambda self, message: messages.append(message)})(),
    })()

    monkeypatch.setattr(loot, "_choose_pack_drop", lambda *_args: None)
    assert not loot._apply_equipment_loot_pickup(ctx, entity)
    assert entity in ctx.game_map.entities
    assert pack == [
        StoredGroundEquipment("armor", "light_helmet"),
        StoredGroundEquipment("armor", "light_vest"),
        StoredGroundEquipment("armor", "combat_boots"),
        StoredGroundEquipment("weapon", "combat_knife"),
    ]
    assert any("full" in message.lower() for message in messages)


def test_full_pack_drop_options_skip_malformed_entries():
    ctx = type("Context", (), {
        "ground_expedition_inventory": [
            StoredGroundEquipment("armor", "missing_armor"),
            StoredGroundEquipment("weapon", "combat_knife"),
        ],
    })()

    assert loot._pack_drop_options(ctx) == ((
        "Drop Combat Knife", "DROP_PACK:1",
    ),)


def test_full_expedition_pack_can_drop_carried_item_for_new_loot(monkeypatch):
    entity = type("Loot", (), {
        "loot_data": {"item_type": "armor", "item_id": "heavy_vest"},
        "pos": type("Position", (), {"x": 2, "y": 2})(),
    })()
    old_entry = StoredGroundEquipment("weapon", "combat_knife")
    pack = [
        StoredGroundEquipment("armor", "light_helmet"),
        StoredGroundEquipment("armor", "light_vest"),
        StoredGroundEquipment("armor", "combat_boots"),
        old_entry,
    ]
    entities = [entity]
    ctx = type("Context", (), {
        "ground_stats": type("Stats", (), {"strength": 10})(),
        "ground_expedition_inventory": pack,
        "game_map": type("Map", (), {"entities": entities})(),
        "log": type("Log", (), {"add": lambda self, _message: None})(),
    })()
    monkeypatch.setattr(loot, "_choose_pack_drop", lambda *_args: 3)

    assert loot._apply_equipment_loot_pickup(ctx, entity)
    assert pack == [
        StoredGroundEquipment("armor", "light_helmet"),
        StoredGroundEquipment("armor", "light_vest"),
        StoredGroundEquipment("armor", "combat_boots"),
        StoredGroundEquipment("armor", "heavy_vest"),
    ]
    assert entity not in entities
    assert any(
        dropped.loot_data == {"item_type": "weapon", "item_id": "combat_knife"}
        for dropped in entities
    )


def test_invalid_equipment_loot_stays_on_floor():
    entity = type("Loot", (), {
        "loot_data": {"item_type": "weapon", "item_id": "missing"},
    })()
    messages = []
    ctx = type("Context", (), {
        "ground_stats": type("Stats", (), {"strength": 10})(),
        "ground_expedition_inventory": [],
        "game_map": type("Map", (), {"entities": [entity]})(),
        "log": type("Log", (), {"add": lambda self, message: messages.append(message)})(),
    })()

    assert not loot._apply_equipment_loot_pickup(ctx, entity)
    assert entity in ctx.game_map.entities
    assert any("unknown" in message.lower() for message in messages)


def test_swap_armor_from_expedition_preserves_replaced_armor():
    equipped = {"body": "light_vest"}
    pack = [StoredGroundEquipment("armor", "heavy_vest")]

    swap_armor_from_expedition(equipped, pack, 0, "body")

    assert equipped == {"body": "heavy_vest"}
    assert pack == [StoredGroundEquipment("armor", "light_vest")]


def test_sell_stored_removes_exactly_one_duplicate():
    storage = [
        StoredGroundEquipment("weapon", "combat_knife"),
        StoredGroundEquipment("weapon", "combat_knife"),
    ]
    assert sell_stored(storage, 1) == StoredGroundEquipment("weapon", "combat_knife")
    assert storage == [StoredGroundEquipment("weapon", "combat_knife")]


# ---------------------------------------------------------------------------
# Weapon instances (design doc 19, Phase 2)
# ---------------------------------------------------------------------------


def test_weapon_instance_seeds_full_magazine_for_reloadable_weapons():
    assert weapon_instance("kinetic_pistol") == GroundWeaponInstance("kinetic_pistol", 12)
    assert weapon_instance("laser_rifle") == GroundWeaponInstance("laser_rifle", 100)


def test_weapon_instance_marks_infinite_weapons_with_none():
    assert weapon_instance("combat_knife") == GroundWeaponInstance("combat_knife", None)
    assert weapon_instance("plasma_pistol") == GroundWeaponInstance("plasma_pistol", None)


def test_weapon_ids_extracts_ids_from_instances():
    instances = [weapon_instance("laser_pistol"), weapon_instance("combat_knife")]
    assert weapon_ids(instances) == ["laser_pistol", "combat_knife"]
    assert weapon_ids([]) == []


def test_parse_weapon_instance_migrates_legacy_string_ids():
    assert parse_weapon_instance("kinetic_rifle") == GroundWeaponInstance("kinetic_rifle", 20)
    assert parse_weapon_instance("fists") == GroundWeaponInstance("fists", None)


def test_parse_weapon_instance_clamps_loaded_ammo_to_capacity():
    assert parse_weapon_instance(
        {"weapon_id": "kinetic_pistol", "loaded_ammo": 999},
    ) == GroundWeaponInstance("kinetic_pistol", 12)
    assert parse_weapon_instance(
        {"weapon_id": "kinetic_pistol", "loaded_ammo": -5},
    ) == GroundWeaponInstance("kinetic_pistol", 0)


def test_parse_weapon_instance_defaults_missing_ammo_to_full_magazine():
    assert parse_weapon_instance(
        {"weapon_id": "kinetic_pistol", "loaded_ammo": None},
    ) == GroundWeaponInstance("kinetic_pistol", 12)
    assert parse_weapon_instance(
        {"weapon_id": "kinetic_pistol"},
    ) == GroundWeaponInstance("kinetic_pistol", 12)


def test_parse_weapon_instance_ignores_malformed_and_unknown_records():
    assert parse_weapon_instance("missing_weapon") is None
    assert parse_weapon_instance(
        {"weapon_id": "missing_weapon", "loaded_ammo": 5},
    ) is None
    assert parse_weapon_instance({"weapon_id": "", "loaded_ammo": 5}) is None
    assert parse_weapon_instance({"loaded_ammo": 5}) is None
    assert parse_weapon_instance(42) is None


def test_parse_weapon_instance_forces_none_for_infinite_weapons():
    # A finite loaded_ammo on an infinite weapon is ignored.
    assert parse_weapon_instance(
        {"weapon_id": "combat_knife", "loaded_ammo": 30},
    ) == GroundWeaponInstance("combat_knife", None)
