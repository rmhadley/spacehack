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
        damage=8, accuracy=65, ap_cost=1, power_cost=2,
        price=60, min_range=1, max_range=5,
        tech_level=2,
    ),
    WeaponSpec(
        id="plasma_cannon", name="Plasma Cannon", slot_type="energy",
        damage=16, accuracy=70, ap_cost=2, power_cost=4,
        price=120, min_range=1, max_range=8,
        tech_level=3,
    ),
)
