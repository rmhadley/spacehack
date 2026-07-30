"""Rifle ground weapons — two-handed ranged primary weapons.

Higher damage, longer range, but require both hands.
"""

from . import GroundWeaponSpec

WARES: tuple[GroundWeaponSpec, ...] = (
    GroundWeaponSpec(
        id="laser_rifle",
        name="Laser Rifle",
        damage_type="energy",
        damage=7,
        accuracy=75,
        ap_cost=2,
        hands=2,
        min_range=1,
        max_range=6,
        ammo_capacity=100,
        price=90,
        tech_level=2,
    ),
    GroundWeaponSpec(
        id="kinetic_rifle",
        name="Kinetic Rifle",
        damage_type="kinetic",
        damage=10,
        accuracy=68,
        ap_cost=2,
        hands=2,
        min_range=2,
        max_range=7,
        ammo_capacity=20,
        price=80,
        tech_level=2,
    ),
    GroundWeaponSpec(
        id="shotgun",
        name="Shotgun",
        damage_type="kinetic",
        damage=12,
        accuracy=60,
        ap_cost=2,
        hands=2,
        min_range=1,
        max_range=4,
        ammo_capacity=8,
        price=70,
        tech_level=1,
    ),
)
