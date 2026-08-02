"""Laser / energy weapons.

All entries share slot_type="energy", ammo_capacity=-1 (no ammo).
Power cost scales with damage output.
"""

from . import WeaponSpec

WEAPONS: tuple[WeaponSpec, ...] = (
    WeaponSpec(
        id="light_laser", name="Light Laser", slot_type="energy",
        damage=4, accuracy=80, ap_cost=1, power_cost=1,
        price=30, min_range=1, max_range=5,
        tech_level=1,
    ),
    WeaponSpec(
        id="medium_laser", name="Medium Laser", slot_type="energy",
        damage=6, accuracy=72, ap_cost=1, power_cost=1,
        price=45, min_range=1, max_range=5,
        tech_level=1,
    ),
    WeaponSpec(
        id="heavy_laser", name="Heavy Laser", slot_type="energy",
        damage=12, accuracy=68, ap_cost=1, power_cost=2,
        price=90, min_range=1, max_range=5,
        tech_level=2,
    ),
)
