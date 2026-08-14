"""Phase 1 tests for the ground field-item model and catalog (design doc 19).

Ammo and consumables are inert catalog data in Phase 1: these tests cover
catalog lookup, stack capacity/validation, the shared malformed-entry
parser, and the transactional pack add/merge helper.
"""

from __future__ import annotations

import pytest

from src.spacehack.data.ground_items import (
    find_ground_ammo,
    find_ground_consumable,
    find_ground_item,
    list_ground_ammo,
    list_ground_consumables,
)
from src.spacehack.ground_equipment import (
    GroundItemStack,
    add_item_quantity,
    add_item_stack,
    expedition_slot_count,
    field_item_capacity,
    item_stack_capacity,
    item_stack_merge_index,
    parse_item_stack,
    transfer_item_stack,
    validate_item_stack,
)


def test_ammo_catalog_resolves_ammo_type_and_stack_size():
    spec = find_ground_ammo("rifle_rounds")
    assert spec.ammo_type == "rifle_round"
    assert spec.rounds_per_stack == 40


def test_consumable_catalog_resolves_effect_and_stack_size():
    spec = find_ground_consumable("med_pack")
    assert spec.effect_id == "restore_hp"
    assert spec.quantity_per_stack == 3
    assert spec.outside_full_heal is True
    assert spec.combat_heal_amount == 5
    assert spec.combat_regen_amount == 2
    assert spec.duration_turns == 3


def test_stim_catalog_duration_and_ap_bonus_are_data_driven():
    spec = find_ground_consumable("stim")
    assert spec.duration_turns == 3
    assert spec.combat_ap_bonus == 1


def test_find_ground_item_dispatches_by_type():
    assert find_ground_item("ammo", "pistol_rounds").name == "Pistol Rounds"
    assert find_ground_item("consumable", "stim").name == "Combat Stim"


def test_find_ground_item_rejects_unknown_type():
    with pytest.raises(KeyError):
        find_ground_item("weapon", "rifle_rounds")


def test_catalogs_list_all_registered_items():
    assert {spec.id for spec in list_ground_ammo()} >= {"rifle_rounds", "energy_cells"}
    assert {spec.id for spec in list_ground_consumables()} >= {"med_pack", "stim"}


def test_item_stack_capacity_reads_both_catalogs():
    assert item_stack_capacity("ammo", "energy_cells") == 50
    assert item_stack_capacity("consumable", "med_pack") == 3


def test_item_stack_capacity_rejects_unknown_type():
    with pytest.raises(ValueError):
        item_stack_capacity("weapon", "laser_pistol")


def test_validate_item_stack_accepts_valid_quantities():
    validate_item_stack(GroundItemStack("ammo", "rifle_rounds", 40))
    validate_item_stack(GroundItemStack("consumable", "med_pack", 1))


def test_validate_item_stack_rejects_zero_and_over_capacity():
    with pytest.raises(ValueError):
        validate_item_stack(GroundItemStack("ammo", "rifle_rounds", 0))
    with pytest.raises(ValueError):
        validate_item_stack(GroundItemStack("ammo", "rifle_rounds", 41))


def test_parse_item_stack_round_trips_a_valid_stack():
    parsed = parse_item_stack(
        {"item_type": "ammo", "item_id": "rifle_rounds", "quantity": 12},
    )
    assert parsed == GroundItemStack("ammo", "rifle_rounds", 12)


def test_parse_item_stack_clamps_over_capacity():
    parsed = parse_item_stack(
        {"item_type": "ammo", "item_id": "shotgun_shells", "quantity": 999},
    )
    assert parsed == GroundItemStack("ammo", "shotgun_shells", 20)


def test_parse_item_stack_ignores_malformed_records():
    assert parse_item_stack("not a dict") is None
    assert parse_item_stack(
        {"item_type": "weapon", "item_id": "rifle_rounds", "quantity": 5},
    ) is None
    assert parse_item_stack(
        {"item_type": "ammo", "item_id": "", "quantity": 5},
    ) is None
    assert parse_item_stack(
        {"item_type": "ammo", "item_id": "rifle_rounds", "quantity": "bad"},
    ) is None
    assert parse_item_stack(
        {"item_type": "ammo", "item_id": "rifle_rounds", "quantity": 0},
    ) is None
    assert parse_item_stack(
        {"item_type": "ammo", "item_id": "missing_ammo", "quantity": 5},
    ) is None


def test_expedition_slot_count_sums_equipment_and_stacks():
    assert expedition_slot_count(["a", "b"], ["x"]) == 3
    assert expedition_slot_count([], []) == 0


def test_item_stack_merge_index_finds_partial_match_only():
    items = [
        GroundItemStack("ammo", "rifle_rounds", 40),  # full
        GroundItemStack("ammo", "pistol_rounds", 10),  # partial, different id
        GroundItemStack("consumable", "med_pack", 1),  # partial, wrong type
    ]
    assert item_stack_merge_index(
        items, GroundItemStack("ammo", "rifle_rounds", 5),
    ) is None
    assert item_stack_merge_index(
        items, GroundItemStack("ammo", "pistol_rounds", 5),
    ) == 1


def test_add_item_stack_merges_into_partial_stack_without_new_slot():
    equipment = []
    items = [GroundItemStack("ammo", "pistol_rounds", 10)]
    remainder = add_item_stack(
        equipment, items, GroundItemStack("ammo", "pistol_rounds", 5), strength=10,
    )
    assert remainder is None
    assert items == [GroundItemStack("ammo", "pistol_rounds", 15)]


def test_add_item_stack_preserves_overflow_in_a_new_stack():
    equipment = []
    items = [GroundItemStack("ammo", "shotgun_shells", 18)]
    remainder = add_item_stack(
        equipment, items, GroundItemStack("ammo", "shotgun_shells", 5), strength=10,
    )
    assert remainder is None
    assert items == [
        GroundItemStack("ammo", "shotgun_shells", 20),
        GroundItemStack("ammo", "shotgun_shells", 3),
    ]


def test_add_item_stack_appends_new_stack_and_uses_a_slot():
    equipment = []
    items = []
    remainder = add_item_stack(
        equipment, items, GroundItemStack("consumable", "med_pack", 2), strength=10,
    )
    assert remainder is None
    assert items == [GroundItemStack("consumable", "med_pack", 2)]


def test_add_item_stack_returns_remainder_when_pack_is_full():
    equipment = ["w1", "w2", "w3", "w4"]  # capacity 4 already used
    items = []
    remainder = add_item_stack(
        equipment, items, GroundItemStack("ammo", "rifle_rounds", 5), strength=10,
    )
    assert remainder == GroundItemStack("ammo", "rifle_rounds", 5)
    assert items == []


def test_add_item_stack_preserves_remainder_when_no_new_slot_exists():
    equipment = ["w1", "w2", "w3"]
    items = [GroundItemStack("ammo", "rifle_rounds", 5)]
    remainder = add_item_stack(
        equipment, items, GroundItemStack("consumable", "med_pack", 1), strength=10,
    )
    assert remainder == GroundItemStack("consumable", "med_pack", 1)
    assert items == [GroundItemStack("ammo", "rifle_rounds", 5)]


def test_field_item_capacity_counts_partial_stacks_and_free_pack_slots():
    equipment = ["weapon"]
    items = [GroundItemStack("ammo", "pistol_rounds", 38)]

    assert field_item_capacity(
        equipment, items, "ammo", "pistol_rounds",
        strength=10, container="expedition",
    ) == 82


def test_add_item_quantity_splits_purchase_into_valid_stacks():
    equipment = []
    items = []

    add_item_quantity(
        equipment, items, "ammo", "pistol_rounds", 45,
        strength=10, container="armory",
    )

    assert items == [
        GroundItemStack("ammo", "pistol_rounds", 40),
        GroundItemStack("ammo", "pistol_rounds", 5),
    ]


def test_add_item_quantity_rejects_pack_overflow_before_mutating():
    equipment = ["w1", "w2", "w3", "w4"]
    items = []

    with pytest.raises(ValueError, match="capacity"):
        add_item_quantity(
            equipment, items, "ammo", "pistol_rounds", 1,
            strength=10, container="expedition",
        )

    assert items == []


def test_transfer_item_stack_merges_into_a_partial_pack_stack():
    source = [GroundItemStack("ammo", "pistol_rounds", 5)]
    destination_equipment = []
    destination = [GroundItemStack("ammo", "pistol_rounds", 35)]

    moved = transfer_item_stack(
        source, destination_equipment, destination, 0,
        destination_container="expedition", strength=10,
    )

    assert moved == GroundItemStack("ammo", "pistol_rounds", 5)
    assert source == []
    assert destination == [GroundItemStack("ammo", "pistol_rounds", 40)]


def test_transfer_item_stack_rejects_full_pack_without_removing_source():
    source = [GroundItemStack("ammo", "pistol_rounds", 5)]
    destination_equipment = ["w1", "w2", "w3", "w4"]
    destination = []

    with pytest.raises(ValueError, match="capacity"):
        transfer_item_stack(
            source, destination_equipment, destination, 0,
            destination_container="expedition", strength=10,
        )

    assert source == [GroundItemStack("ammo", "pistol_rounds", 5)]
    assert destination == []
