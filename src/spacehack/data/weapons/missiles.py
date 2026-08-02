"""Missile / projectile weapons.

All entries share slot_type="missile", power_cost=0 (no power needed).
Ammo is now *persistent*: rounds spent in combat stay spent until
rebought at the mechanic via ``ammo_price`` per round. ``ammo_capacity``
is the max magazine; each round uses ``cargo_per_round`` cargo space
permanently reserved. Long min_range means point-blank firing eats the
min-range accuracy penalty — missiles are kiting weapons.
"""

from . import WeaponSpec

WEAPONS: tuple[WeaponSpec, ...] = (
    WeaponSpec(
        id="light_missile", name="Light Missile", slot_type="missile",
        damage=14, accuracy=72, ap_cost=2, power_cost=0,
        ammo_capacity=4, ammo_per_shot=1, cargo_per_round=2,
        ammo_price=8, price=40, min_range=2, max_range=9,
        tech_level=1,
    ),
    WeaponSpec(
        id="heavy_missile", name="Heavy Missile", slot_type="missile",
        damage=28, accuracy=65, ap_cost=2, power_cost=0,
        ammo_capacity=3, ammo_per_shot=1, cargo_per_round=3,
        ammo_price=20, price=90, min_range=3, max_range=11,
        tech_level=3,
    ),
    WeaponSpec(
        id="emp_missile", name="EMP Missile", slot_type="missile",
        damage=0, accuracy=75, ap_cost=2, power_cost=0,
        ammo_capacity=2, ammo_per_shot=1, cargo_per_round=2,
        ammo_price=25, price=120, min_range=2, max_range=10,
        tech_level=4, shield_strip=20,
    ),
)
