"""Explosive ground weapons — heavy burst damage with a finite magazine.

All entries share ``damage_type="explosive"`` and a limited ammo
capacity. Real reload/ammo mechanics land with the ammo/field-items
pass (design doc 19).
"""

from . import GroundWeaponSpec

WARES: tuple[GroundWeaponSpec, ...] = (
    GroundWeaponSpec(
        id="grenade_launcher",
        name="Grenade Launcher",
        damage_type="explosive",
        damage=15,
        accuracy=62,
        ap_cost=2,
        hands=2,
        min_range=3,
        max_range=7,
        ammo_capacity=6,
        price=480,
        tech_level=3,
    ),
    GroundWeaponSpec(
        id="rocket_launcher",
        name="Rocket Launcher",
        damage_type="explosive",
        damage=30,
        accuracy=58,
        ap_cost=3,
        hands=2,
        min_range=2,
        max_range=9,
        ammo_capacity=4,
        price=1100,
        tech_level=4,
    ),
)
