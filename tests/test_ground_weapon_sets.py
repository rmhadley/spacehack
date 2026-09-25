"""Doc 51 phase 1 tests: set classification, slot law, swap, migration split."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.spacehack import ground_weapon_sets
from src.spacehack.data.ground_weapons import list_ground_weapons
from src.spacehack.ground_equipment import GroundWeaponInstance


def test_classification_covers_every_catalog_weapon():
    """Every registered weapon (monsters included) resolves to a set."""
    classes = {ground_weapon_sets.weapon_set(w.id) for w in list_ground_weapons()}
    assert classes == {"ranged", "melee"}


def test_classification_domain_spans_all_five_damage_types():
    """The catalog exercises the whole table domain — exhaustiveness is
    load-bearing (an unseen family must fail, not silently join)."""
    damage_types = {w.damage_type for w in list_ground_weapons()}
    assert damage_types == {"melee", "kinetic", "energy", "plasma", "explosive"}


def test_classification_maps_representative_ids():
    assert ground_weapon_sets.weapon_set("railgun") == "ranged"
    assert ground_weapon_sets.weapon_set("kinetic_pistol") == "ranged"
    assert ground_weapon_sets.weapon_set("plasma_rifle") == "ranged"
    assert ground_weapon_sets.weapon_set("rocket_launcher") == "ranged"
    assert ground_weapon_sets.weapon_set("combat_knife") == "melee"
    assert ground_weapon_sets.weapon_set("mono_blade") == "melee"


def test_unknown_damage_type_raises(monkeypatch):
    """A future damage type outside the table fails loudly."""
    monkeypatch.setattr(
        ground_weapon_sets, "find_ground_weapon",
        lambda _wid: SimpleNamespace(damage_type="sonic"),
    )
    with pytest.raises(ValueError, match="sonic"):
        ground_weapon_sets.weapon_set("future_gun")


def test_empty_set_accepts_either_class():
    """An empty set is class-agnostic; occupancy counts from zero."""
    assert ground_weapon_sets.can_fit_weapon_set([], "kinetic_pistol")
    assert ground_weapon_sets.can_fit_weapon_set([], "combat_knife")
    assert ground_weapon_sets.can_fit_weapon_set([], "railgun")


def test_two_one_handed_same_class_fits():
    knife = GroundWeaponInstance("combat_knife", None)
    assert ground_weapon_sets.can_fit_weapon_set([knife], "vibroblade")
    pistol = GroundWeaponInstance("kinetic_pistol", 5)
    assert ground_weapon_sets.can_fit_weapon_set([pistol], "smg")


def test_two_handed_fits_alone_and_refuses_company():
    assert ground_weapon_sets.can_fit_weapon_set([], "railgun")
    railgun = GroundWeaponInstance("railgun", 3)
    assert not ground_weapon_sets.can_fit_weapon_set([railgun], "kinetic_pistol")
    mono = GroundWeaponInstance("mono_blade", None)
    assert not ground_weapon_sets.can_fit_weapon_set([mono], "combat_knife")


def test_three_one_handed_refused():
    knife = GroundWeaponInstance("combat_knife", None)
    baton = GroundWeaponInstance("stun_baton", None)
    assert not ground_weapon_sets.can_fit_weapon_set([knife, baton], "vibroblade")


def test_class_mix_refused_even_with_room():
    """A 1H melee never joins a ranged set (class purity, not just Σ hands)."""
    pistol = GroundWeaponInstance("kinetic_pistol", 5)
    assert not ground_weapon_sets.can_fit_weapon_set([pistol], "combat_knife")
    knife = GroundWeaponInstance("combat_knife", None)
    assert not ground_weapon_sets.can_fit_weapon_set([knife], "smg")


def test_exchange_swaps_lists_in_place():
    """The original list objects are mutated — callers holding
    ctx.equipped_ground_weapons / ctx.holstered_ground_weapons see the
    swap without rebinding."""
    equipped = [GroundWeaponInstance("kinetic_pistol", 5, 1)]
    holstered = [GroundWeaponInstance("combat_knife", None, 2)]
    equipped_ref, holstered_ref = equipped, holstered
    ground_weapon_sets.exchange_weapon_sets(equipped, holstered)
    assert equipped_ref == [GroundWeaponInstance("combat_knife", None, 2)]
    assert holstered_ref == [GroundWeaponInstance("kinetic_pistol", 5, 1)]


def test_exchange_moves_instances_not_copies():
    """Magazines + quality ride the SAME instance objects — no reseed."""
    pistol = GroundWeaponInstance("smg", 7, 3)
    holstered: list[GroundWeaponInstance] = []
    ground_weapon_sets.exchange_weapon_sets([pistol], holstered)
    assert holstered == [GroundWeaponInstance("smg", 7, 3)]
    assert holstered[0] is pistol


def test_exchange_with_either_side_empty():
    """Empty↔full both directions — the fists floor (SETTLED 1)."""
    pistol = GroundWeaponInstance("kinetic_pistol", 2)
    equipped, holstered = [pistol], []
    ground_weapon_sets.exchange_weapon_sets(equipped, holstered)
    assert (equipped, holstered) == ([], [pistol])
    ground_weapon_sets.exchange_weapon_sets(equipped, holstered)
    assert (equipped, holstered) == ([pistol], [])


def test_double_exchange_is_identity():
    equipped = [GroundWeaponInstance("railgun", 4, 1)]
    holstered = [
        GroundWeaponInstance("combat_knife", None, 2),
        GroundWeaponInstance("vibroblade", None),
    ]
    snapshot = (list(equipped), list(holstered))
    ground_weapon_sets.exchange_weapon_sets(equipped, holstered)
    ground_weapon_sets.exchange_weapon_sets(equipped, holstered)
    assert (equipped, holstered) == snapshot


def test_partition_keeps_same_class_loadout_together():
    weapons = [
        GroundWeaponInstance("kinetic_pistol", 3),
        GroundWeaponInstance("smg", 9, 2),
    ]
    active, holstered = ground_weapon_sets.partition_weapon_sets(weapons)
    assert active == weapons
    assert holstered == []


def test_partition_splits_mixed_pair_on_slot_zero_class():
    """Active = the ORIGINAL slot 0's class; the other class holsters."""
    pistol = GroundWeaponInstance("kinetic_pistol", 3)
    knife = GroundWeaponInstance("combat_knife", None, 1)
    active, holstered = ground_weapon_sets.partition_weapon_sets([pistol, knife])
    assert active == [pistol]
    assert holstered == [knife]
    active, holstered = ground_weapon_sets.partition_weapon_sets([knife, pistol])
    assert active == [knife]
    assert holstered == [pistol]


def test_partition_empty_loadout_yields_two_empty_sets():
    assert ground_weapon_sets.partition_weapon_sets([]) == ([], [])
