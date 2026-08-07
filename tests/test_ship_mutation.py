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

from src.spacehack.ship import OwnedShip, _install_weapon, _remove_weapon


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
