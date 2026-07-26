"""Laser / energy weapons.

All entries share slot_type="energy", ammo_capacity=-1 (no ammo).
Power cost scales with damage output.
"""

from . import WeaponSpec

WEAPONS: tuple[WeaponSpec, ...] = (
    WeaponSpec(
        id="light_laser", name="Light Laser", slot_type="energy",
        damage=3, accuracy=80, ap_cost=1, power_cost=2,
        min_range=1, max_range=4,
    ),
    WeaponSpec(
        id="heavy_laser", name="Heavy Laser", slot_type="energy",
        damage=8, accuracy=65, ap_cost=1, power_cost=6,
        min_range=1, max_range=5,
    ),
    WeaponSpec(
        id="plasma_cannon", name="Plasma Cannon", slot_type="energy",
        damage=15, accuracy=70, ap_cost=2, power_cost=7,
        min_range=1, max_range=6,
    ),
)
