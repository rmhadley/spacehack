"""Tests for ship mutation — weapon install/remove, ammo re-indexing.

Ammo is keyed by weapon SLOT index. When a weapon is removed,
slots above it shift down — the ammo dict must be re-indexed
correctly or magazines silently attach to wrong weapons.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.ship import (
    OwnedShip,
    StoredEquipment,
    _install_weapon,
    _remove_weapon,
    can_install_stored_equipment,
    install_stored_equipment,
    move_installed_equipment_to_storage,
    store_module,
    store_weapon,
)


def _scout_spec() -> SimpleNamespace:
    """A ship spec with 2 weapon slots."""
    return SimpleNamespace(weapon_slots=2, module_slots=2)


class TestInstallWeapon:
    def test_install_fills_slot(self):
        owned = OwnedShip(ship_id="scout", weapons=(), modules=())
        spec = _scout_spec()
        ok = _install_weapon(owned, "light_laser", spec)
        assert ok is True
        assert owned.weapons == ("light_laser",)

    def test_install_full_slots(self):
        owned = OwnedShip(ship_id="scout", weapons=("light_laser", "medium_laser"), modules=())
        spec = _scout_spec()
        ok = _install_weapon(owned, "heavy_laser", spec)
        assert ok is False
        assert len(owned.weapons) == 2  # unchanged

    def test_install_missile_seeds_ammo(self):
        """Installing a missile weapon seeds a full magazine at the new slot."""
        owned = OwnedShip(ship_id="scout", weapons=(), modules=())
        spec = _scout_spec()
        ok = _install_weapon(owned, "light_missile", spec)
        assert ok is True
        # light_missile has ammo_capacity=4, lives in slot 0.
        assert owned.weapon_ammo[0] == 4

    def test_install_energy_no_ammo(self):
        """Installing an energy weapon does not add an ammo entry."""
        owned = OwnedShip(ship_id="scout", weapons=(), modules=())
        spec = _scout_spec()
        _install_weapon(owned, "light_laser", spec)
        # Energy weapons don't get ammo entries.
        assert 0 not in owned.weapon_ammo


class TestRemoveWeapon:
    def test_remove_shifts_down(self):
        """Removing slot 0 shifts slot 1's weapon into slot 0."""
        owned = OwnedShip(
            ship_id="scout",
            weapons=("light_laser", "medium_laser"),
        )
        owned.weapon_ammo = {0: -1, 1: 12}  # slot 1 has ammo
        new = _remove_weapon(owned, 0)
        assert new == ("medium_laser",)
        # Ammo shifted: old slot 1 → new slot 0
        assert owned.weapon_ammo == {0: 12}

    def test_remove_last_weapon(self):
        owned = OwnedShip(ship_id="scout", weapons=("light_laser",))
        owned.weapon_ammo = {0: -1}
        new = _remove_weapon(owned, 0)
        assert new == ()
        assert owned.weapon_ammo == {}

    def test_remove_middle_slot(self):
        """Removing slot 1 from 3 weapons: slots above shift down."""
        owned = OwnedShip(
            ship_id="freightliner",
            weapons=("light_laser", "medium_laser", "heavy_laser"),
        )
        owned.weapon_ammo = {0: -1, 1: 8, 2: -1}
        new = _remove_weapon(owned, 1)
        assert new == ("light_laser", "heavy_laser")
        assert owned.weapon_ammo == {0: -1, 1: -1}

    def test_remove_out_of_range_noop(self):
        owned = OwnedShip(ship_id="scout", weapons=("light_laser",))
        new = _remove_weapon(owned, 5)
        assert new == ("light_laser",)  # unchanged

    def test_sold_ammo_vanishes(self):
        """The removed weapon's ammo entry is discarded."""
        owned = OwnedShip(
            ship_id="scout",
            weapons=("light_missile", "light_laser"),
        )
        owned.weapon_ammo = {0: 4, 1: -1}
        _remove_weapon(owned, 0)
        # Old slot 0 ammo is gone; old slot 1 shifts to 0.
        assert 0 in owned.weapon_ammo  # old slot 1 now at 0
        assert 1 not in owned.weapon_ammo  # old slot 0 discarded


class TestEquipmentStorage:
    def test_store_weapon_preserves_partial_missile_ammo(self):
        owned = OwnedShip(ship_id="scout", weapons=("light_missile",))
        owned.weapon_ammo[0] = 2
        storage = []

        assert store_weapon(owned, storage, 0) is True
        assert owned.weapons == ()
        assert storage == [StoredEquipment("weapon", "light_missile", 2)]

    def test_store_module_preserves_duplicate_parts(self):
        owned = OwnedShip(
            ship_id="scout",
            modules=(StoredEquipment("module", "shield_mk1"),) * 2,
        )
        storage = []

        assert store_module(owned, storage, 0) is True
        assert store_module(owned, storage, 0) is True
        assert storage == [
            StoredEquipment("module", "shield_mk1"),
            StoredEquipment("module", "shield_mk1"),
        ]

    def test_install_stored_missile_restores_partial_ammo(self):
        owned = OwnedShip(ship_id="scout")
        storage = [StoredEquipment("weapon", "light_missile", 1)]

        assert install_stored_equipment(
            owned, storage, 0, _scout_spec(),
        ) is True
        assert owned.weapons == ("light_missile",)
        assert owned.weapon_ammo == {0: 1}
        assert storage == []

    def test_incompatible_storage_entry_stays_in_storage(self):
        owned = OwnedShip(
            ship_id="starter",
            weapons=("light_laser", "light_laser"),
        )
        storage = [StoredEquipment("weapon", "heavy_laser")]

        assert can_install_stored_equipment(
            owned, storage[0], SimpleNamespace(weapon_slots=2, module_slots=1),
        ) is False
        assert install_stored_equipment(
            owned, storage, 0, SimpleNamespace(weapon_slots=2, module_slots=1),
        ) is False
        assert storage == [StoredEquipment("weapon", "heavy_laser")]

    def test_invalid_indexes_are_noops(self):
        owned = OwnedShip(ship_id="scout", weapons=("light_laser",))
        storage = []

        assert store_weapon(owned, storage, 4) is False
        assert store_module(owned, storage, -1) is False
        assert install_stored_equipment(
            owned, storage, 0, _scout_spec(),
        ) is False
        assert owned.weapons == ("light_laser",)
        assert storage == []

    def test_bulk_transfer_validates_before_mutating(self):
        owned = OwnedShip(
            ship_id="scout",
            weapons=("missing_weapon", "light_laser"),
        )
        storage = []

        import pytest
        with pytest.raises(ValueError):
            move_installed_equipment_to_storage(owned, storage)
        assert owned.weapons == ("missing_weapon", "light_laser")
        assert storage == []

    def test_move_all_installed_equipment_to_storage(self):
        owned = OwnedShip(
            ship_id="scout",
            weapons=("light_laser", "light_missile"),
            modules=(StoredEquipment("module", "shield_mk1"),),
        )
        owned.weapon_ammo[1] = 2
        storage = []

        move_installed_equipment_to_storage(owned, storage)

        assert owned.weapons == ()
        assert owned.modules == ()
        assert storage == [
            StoredEquipment("weapon", "light_laser"),
            StoredEquipment("weapon", "light_missile", 2),
            StoredEquipment("module", "shield_mk1"),
        ]


class TestModuleQualityInstances:
    """Installed modules are quality-bearing instances (doc 47.3)."""

    def test_install_store_round_trip_preserves_quality(self):
        owned = OwnedShip(ship_id="scout")
        storage = [StoredEquipment("module", "shield_mk2", quality=2)]

        assert install_stored_equipment(owned, storage, 0, _scout_spec())
        assert owned.modules == (StoredEquipment("module", "shield_mk2", quality=2),)
        assert store_module(owned, storage, 0)
        assert storage == [StoredEquipment("module", "shield_mk2", quality=2)]

    def test_bulk_transfer_preserves_quality(self):
        owned = OwnedShip(
            ship_id="scout",
            modules=(
                StoredEquipment("module", "compact_reactor", quality=1),
                StoredEquipment("module", "armor_plating", quality=3),
            ),
        )
        storage = []

        move_installed_equipment_to_storage(owned, storage)

        assert owned.modules == ()
        assert storage == [
            StoredEquipment("module", "compact_reactor", quality=1),
            StoredEquipment("module", "armor_plating", quality=3),
        ]

    def test_base_entries_wrap_bare_ids(self):
        from src.spacehack.ship import base_module_entries

        assert base_module_entries(("shield_mk1",)) == (
            StoredEquipment("module", "shield_mk1"),
        )

    def test_parse_module_entry_migrates_legacy_shapes(self):
        from src.spacehack.ship import parse_module_entry

        # Legacy bare id -> base instance.
        assert parse_module_entry("shield_mk1") == StoredEquipment(
            "module", "shield_mk1",
        )
        # Instance dict keeps its quality; malformed quality -> base.
        assert parse_module_entry(
            {"item_type": "module", "item_id": "shield_mk2", "quality": 3},
        ) == StoredEquipment("module", "shield_mk2", quality=3)
        assert parse_module_entry(
            {"item_type": "module", "item_id": "shield_mk2", "quality": "junk"},
        ) == StoredEquipment("module", "shield_mk2")
        # Unknown ids and malformed records drop.
        assert parse_module_entry("no_such_module") is None
        assert parse_module_entry(42) is None
        assert parse_module_entry({"item_id": ""}) is None
