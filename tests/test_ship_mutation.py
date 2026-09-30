"""Tests for ship mutation — weapon install/remove, ammo re-indexing.

Ammo is keyed by weapon SLOT index. When a weapon is removed,
slots above it shift down — the ammo dict must be re-indexed
correctly or magazines silently attach to wrong weapons.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.data.ships import find_ship
from src.spacehack.ship import (
    OwnedShip,
    StoredEquipment,
    INSTALL_REFUSAL_POWER,
    INSTALL_REFUSAL_ROOM,
    _install_weapon,
    _remove_weapon,
    install_refusal,
    install_stored_equipment,
    move_installed_equipment_to_storage,
    normalize_fitted_grid,
    removal_trips_power,
    resting_power,
    start_fitted_entries,
    store_module,
    store_weapon,
)


class TestInstallWeapon:
    def test_install_appends_entry(self):
        owned = OwnedShip(ship_id="scout", weapons=(), modules=())
        ok = _install_weapon(owned, "light_laser")
        assert ok is True
        assert tuple(e.item_id for e in owned.weapons) == ("light_laser",)

    def test_beyond_slots_installs_on_the_grid(self):
        # Doc 56 phase 3: the slot guard retired with the slot
        # summaries — the Skiff has 2 weapon slots and a 3x3 grid, so
        # a third 1x1 laser LANDS (grid legality, never slot counts).
        owned = OwnedShip(
            ship_id="starter", weapons=("light_laser", "light_laser"),
        )
        assert _install_weapon(owned, "light_laser")
        assert len(owned.weapons) == 3

    def test_install_missile_seeds_ammo(self):
        """Installing a missile weapon seeds a full magazine at the new slot."""
        owned = OwnedShip(ship_id="scout", weapons=(), modules=())
        ok = _install_weapon(owned, "light_missile")
        assert ok is True
        # light_missile has ammo_capacity=4, lives in slot 0.
        assert owned.weapon_ammo[0] == 4

    def test_install_energy_no_ammo(self):
        """Installing an energy weapon does not add an ammo entry."""
        owned = OwnedShip(ship_id="scout", weapons=(), modules=())
        _install_weapon(owned, "light_laser")
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
        assert tuple(e.item_id for e in new) == ("medium_laser",)
        # Ammo shifted: old slot 1 → new slot 0
        assert owned.weapon_ammo == {0: 12}

    def test_remove_last_weapon(self):
        owned = OwnedShip(ship_id="scout", weapons=("light_laser",))
        owned.weapon_ammo = {0: -1}
        new = _remove_weapon(owned, 0)
        assert tuple(e.item_id for e in new) == ()
        assert owned.weapon_ammo == {}

    def test_remove_middle_slot(self):
        """Removing slot 1 from 3 weapons: slots above shift down."""
        owned = OwnedShip(
            ship_id="freightliner",
            weapons=("light_laser", "medium_laser", "heavy_laser"),
        )
        owned.weapon_ammo = {0: -1, 1: 8, 2: -1}
        new = _remove_weapon(owned, 1)
        assert tuple(e.item_id for e in new) == ("light_laser", "heavy_laser")
        assert owned.weapon_ammo == {0: -1, 1: -1}

    def test_remove_out_of_range_noop(self):
        owned = OwnedShip(ship_id="scout", weapons=("light_laser",))
        new = _remove_weapon(owned, 5)
        assert tuple(e.item_id for e in new) == ("light_laser",)  # unchanged

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
        assert tuple(e.item_id for e in owned.weapons) == ()
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
            owned, storage, 0, find_ship("scout"),
        ) is True
        assert tuple(e.item_id for e in owned.weapons) == ("light_missile",)
        assert owned.weapon_ammo == {0: 1}
        assert storage == []

    def test_beyond_slots_stored_install_lands_on_the_grid(self):
        # Doc 56 phase 3: slot counts no longer refuse an install —
        # the starter's 2 weapon slots hold a third laser because the
        # 3x3 grid has the room (phase-3 brief blocking 1's pin).
        owned = OwnedShip(
            ship_id="starter",
            weapons=(
                StoredEquipment("weapon", "light_laser", grid_x=0, grid_y=0),
                StoredEquipment("weapon", "light_laser", grid_x=1, grid_y=0),
            ),
        )
        storage = [StoredEquipment("weapon", "light_laser")]

        assert install_refusal(
            owned, storage[0], find_ship("starter"),
        ) is None
        assert install_stored_equipment(
            owned, storage, 0, find_ship("starter"),
        )
        assert tuple(e.grid_x for e in owned.weapons) == (0, 1, 2)
        assert storage == []

    def test_invalid_indexes_are_noops(self):
        owned = OwnedShip(ship_id="scout", weapons=("light_laser",))
        storage = []

        assert store_weapon(owned, storage, 4) is False
        assert store_module(owned, storage, -1) is False
        assert install_stored_equipment(
            owned, storage, 0, find_ship("scout"),
        ) is False
        assert tuple(e.item_id for e in owned.weapons) == ("light_laser",)
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
        assert tuple(e.item_id for e in owned.weapons) == ("missing_weapon", "light_laser")
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

        assert tuple(e.item_id for e in owned.weapons) == ()
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

        assert install_stored_equipment(owned, storage, 0, find_ship("scout"))
        # Installed = placed (doc 56 phase 2): the stamp rides the
        # quality; storing strips it back to a position-less payload.
        assert owned.modules == (
            StoredEquipment(
                "module", "shield_mk2", quality=2, grid_x=0, grid_y=0,
            ),
        )
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


class TestBuyAmmoCargoSync:
    def test_magazine_buy_recalc_cargo_ammo(self):
        """buy_ammo keeps cargo_ammo == total_ammo_cargo (doc 48.3 punch)."""
        from src.spacehack.ship import buy_ammo, total_ammo_cargo

        owned = OwnedShip(
            ship_id="scout", weapons=("light_missile",), modules=(),
        )
        # Simulate a stale reserve (e.g. legacy save): cargo off by 3.
        owned.cargo_ammo = total_ammo_cargo(owned.weapons) - 3
        owned.weapon_ammo = {0: 0}  # magazine emptied by combat
        ok, _cost, _reason = buy_ammo(owned, 0, 1, credits=10_000)
        assert ok is True
        assert owned.cargo_ammo == total_ammo_cargo(owned.weapons)


class TestFittingGate:
    """Doc 56 phase 2: the resting power gate — install refusals,
    symmetric removal, placements on the ammo coupling, and the
    load-time normalization."""

    def test_ac1_fresh_skiff_cannot_field_shield_mk4(self):
        # AC1: the FRESH skiff (its start laser aboard) cannot field a
        # Shield Mk. 4 by any path — the 3x3 shield needs all nine
        # cells and the laser holds one. CHECKPOINT-RULED MECHANISM:
        # the brief's power-side refusal (3 - 4 < 0) was authored
        # against base gen 3; the goal-1 re-fund (base 4, doc 50's
        # ruled equilibrium restored after upkeep) moves the refusal
        # to geometry for the fresh ship. See the phase-2 checkpoint.
        owned, _modules = start_fitted_entries(find_ship("starter"))
        fresh = OwnedShip(ship_id="starter", weapons=owned)
        storage = [StoredEquipment("module", "shield_mk4")]

        assert install_refusal(fresh, storage[0], find_ship("starter")) == (
            INSTALL_REFUSAL_ROOM
        )
        assert install_stored_equipment(fresh, storage, 0, find_ship("starter")) is False

    def test_empty_skiff_shield_mk4_leaves_zero_headroom(self):
        # On an EMPTY skiff the bare shield_mk4 fields at net 0 (4-4);
        # the pin that survives any retune: zero headroom — the next
        # upkept part refuses on POWER. Scout for the free module slot.
        owned = OwnedShip(ship_id="scout")
        storage = [StoredEquipment("module", "shield_mk3")]
        assert install_stored_equipment(owned, storage, 0, find_ship("scout"))
        assert resting_power(owned, find_ship("scout")) == 0  # 3 - 3

        storage = [StoredEquipment("module", "targeting_computer")]
        assert install_refusal(owned, storage[0], find_ship("scout")) == (
            INSTALL_REFUSAL_POWER
        )

    def test_reactor_mk4_installs_when_power_funds_it(self):
        owned = OwnedShip(ship_id="starter")
        storage = [StoredEquipment("module", "reactor_mk4")]

        assert install_stored_equipment(owned, storage, 0, find_ship("starter"))
        entry = owned.modules[0]
        assert (entry.grid_x, entry.grid_y) == (0, 0)  # 3x3 fills the grid

    def test_room_refusal_when_no_cell_fits(self):
        # Scout 4x3 with shield_mk4 on columns 0-2 and a missile rack
        # on column 3 rows 0-1: one free cell (3,2), no 1x2 anchor —
        # a second rack has weapon slots and power to spare, but no
        # room.
        owned = OwnedShip(
            ship_id="scout",
            weapons=(
                StoredEquipment("weapon", "light_missile", grid_x=3, grid_y=0),
            ),
            modules=(
                StoredEquipment("module", "shield_mk4", grid_x=0, grid_y=0),
            ),
        )
        storage = [StoredEquipment("weapon", "light_missile")]

        assert install_refusal(owned, storage[0], find_ship("scout")) == (
            INSTALL_REFUSAL_ROOM
        )

    def test_removal_gate_symmetric_on_funding_reactor(self):
        # SETTLED 3: scout 3 + reactor 3 - shield_mk4 4 = +2 resting;
        # removing the reactor would leave -1, so the removal refuses.
        owned = OwnedShip(ship_id="scout", modules=(
            StoredEquipment("module", "compact_reactor", grid_x=0, grid_y=0),
            StoredEquipment("module", "shield_mk4", grid_x=1, grid_y=0),
        ))
        spec = find_ship("scout")
        assert resting_power(owned, spec) == 2
        assert removal_trips_power(owned, spec, "module", 0) is True
        assert removal_trips_power(owned, spec, "module", 1) is False  # shield: net improves
        assert removal_trips_power(owned, spec, "weapon", 0) is False  # weapons never upkeep

    def test_ammo_coupling_survives_a_placement_stamped_removal(self):
        # Store the MIDDLE missile of three placed launchers: the
        # magazines re-key and the survivors keep their anchors.
        placed = (
            StoredEquipment("weapon", "light_missile", grid_x=0, grid_y=0),
            StoredEquipment("weapon", "heavy_missile", grid_x=1, grid_y=0),
            StoredEquipment("weapon", "light_missile", grid_x=2, grid_y=0),
        )
        owned = OwnedShip(ship_id="frigate", weapons=placed)
        owned.weapon_ammo = {0: 1, 1: 2, 2: 3}
        storage = []

        assert store_weapon(owned, storage, 1)
        assert tuple((e.item_id, e.grid_x, e.grid_y) for e in owned.weapons) == (
            ("light_missile", 0, 0), ("light_missile", 2, 0),
        )
        assert owned.weapon_ammo == {0: 1, 1: 3}
        assert storage == [StoredEquipment("weapon", "heavy_missile", 2)]

    def test_resting_power_scales_with_quality_and_clamps_distinction(self):
        from src.spacehack.combat._stats import _calc_power_gen

        spec = find_ship("starter")
        base = StoredEquipment("module", "shield_mk1")
        raised = StoredEquipment("module", "shield_mk1", quality=1)
        assert resting_power(OwnedShip(ship_id="starter", modules=(base,)), spec) == 3
        # -1 scaled 1.15 -> -2 (ceiling in magnitude): 4 - 2 = 2.
        assert resting_power(OwnedShip(ship_id="starter", modules=(raised,)), spec) == 2
        # Clamp pin: the combat pool is exactly the gate's clamp.
        for modules in ((base,), (raised,), (base, raised)):
            owned = OwnedShip(ship_id="starter", modules=modules)
            signed = resting_power(owned, spec)
            assert _calc_power_gen(spec, modules) == max(0, signed)

    def test_resting_power_applies_randart_axis(self):
        from src.spacehack.data.randarts import roll_randart

        spec = find_ship("starter")
        seed = next(
            s for s in range(200)
            if dict(roll_randart("compact_reactor", s).axes).get("power_gen_bonus")
        )
        axis = dict(roll_randart("compact_reactor", seed).axes)["power_gen_bonus"]
        owned = OwnedShip(
            ship_id="starter",
            modules=(StoredEquipment("module", "compact_reactor", randart_seed=seed),),
        )
        assert resting_power(owned, spec) == 4 + 3 + axis

    def test_normalize_strips_placementless_entries(self):
        owned = OwnedShip(
            ship_id="starter",
            weapons=(StoredEquipment("weapon", "light_laser"),),
            modules=(StoredEquipment("module", "shield_mk1"),),
        )
        storage = []

        labels = normalize_fitted_grid(owned, storage, find_ship("starter"))

        assert owned.weapons == () and owned.modules == ()
        # Weapons scan (and store) before modules — deterministic.
        assert storage == [
            StoredEquipment("weapon", "light_laser"),
            StoredEquipment("module", "shield_mk1"),
        ]
        assert labels == ["Light Laser", "Shield Mk. 1"]

    def test_normalize_strips_highest_upkeep_first_with_later_position_ties(self):
        # 4 - 2 - 2 - 2 < 0: three q1 shields tie at -2 (the 1x2 reshape
        # fits all three on the skiff legally, SETTLED 26); the LATER
        # entry strips first, leaving a legal grid at exactly net 0.
        owned = OwnedShip(ship_id="starter", modules=(
            StoredEquipment("module", "shield_mk1", quality=1, grid_x=0, grid_y=0),
            StoredEquipment("module", "shield_mk1", quality=1, grid_x=1, grid_y=0),
            StoredEquipment("module", "shield_mk1", quality=1, grid_x=2, grid_y=0),
        ))
        storage = []

        labels = normalize_fitted_grid(owned, storage, find_ship("starter"))

        assert tuple(e.grid_x for e in owned.modules) == (0, 1)
        assert resting_power(owned, find_ship("starter")) == 0
        assert labels == ["Modded Shield Mk. 1"]

    def test_normalize_strips_later_entry_on_within_tuple_overlap(self):
        owned = OwnedShip(ship_id="scout", modules=(
            StoredEquipment("module", "shield_mk1", grid_x=0, grid_y=0),
            StoredEquipment("module", "shield_mk2", grid_x=0, grid_y=0),
        ))
        storage = []

        labels = normalize_fitted_grid(owned, storage, find_ship("scout"))

        assert tuple(e.item_id for e in owned.modules) == ("shield_mk1",)
        assert labels == ["Shield Mk. 2"]

    def test_normalize_strips_module_on_cross_tuple_overlap(self):
        # One grid, two tuples, one rule: weapons win the cells.
        owned = OwnedShip(
            ship_id="scout",
            weapons=(StoredEquipment("weapon", "heavy_laser", grid_x=0, grid_y=0),),
            modules=(StoredEquipment("module", "shield_mk1", grid_x=0, grid_y=0),),
        )
        storage = []

        labels = normalize_fitted_grid(owned, storage, find_ship("scout"))

        assert owned.weapons[0].item_id == "heavy_laser"
        assert owned.modules == ()
        assert labels == ["Shield Mk. 1"]

    def test_normalize_strips_out_of_bounds_placement(self):
        owned = OwnedShip(ship_id="starter", modules=(
            StoredEquipment("module", "shield_mk1", grid_x=2, grid_y=2),
        ))
        storage = []

        labels = normalize_fitted_grid(owned, storage, find_ship("starter"))

        assert owned.modules == ()
        assert labels == ["Shield Mk. 1"]
