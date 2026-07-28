"""Missile / projectile weapons.

All entries share slot_type="missile", power_cost=0 (no power needed).
Ammo is consumed from cargo. ammo_capacity is the max carried; each
round uses cargo_per_round cargo space.
"""

from . import WeaponSpec

WEAPONS: tuple[WeaponSpec, ...] = (
    WeaponSpec(
        id="light_missile", name="Light Missile", slot_type="missile",
        damage=10, accuracy=75, ap_cost=2, power_cost=0,
        ammo_capacity=5, ammo_per_shot=1, cargo_per_round=1,
        price=25, min_range=1, max_range=6,
        tech_level=1,
    ),
    WeaponSpec(
        id="heavy_missile", name="Heavy Missile", slot_type="missile",
        damage=20, accuracy=60, ap_cost=2, power_cost=0,
        ammo_capacity=3, ammo_per_shot=1, cargo_per_round=2,
        price=50, min_range=2, max_range=7,
        tech_level=3,
    ),
    WeaponSpec(
        id="emp_missile", name="EMP Missile", slot_type="missile",
        damage=0, accuracy=70, ap_cost=2, power_cost=0,
        ammo_capacity=2, ammo_per_shot=1, cargo_per_round=2,
        price=75, min_range=1, max_range=5,
        tech_level=4,
    ),
)
