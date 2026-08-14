"""Pistol ground weapons — one-handed ranged sidearms.

Kinetic pistols have limited ammo; energy pistols have high ammo
(rechargeable). All share hands=1.
"""

from . import GroundWeaponSpec

WARES: tuple[GroundWeaponSpec, ...] = (
    GroundWeaponSpec(
        id="laser_pistol",
        name="Laser Pistol",
        damage_type="energy",
        damage=4,
        accuracy=78,
        ap_cost=1,
        hands=1,
        min_range=1,
        max_range=4,
        ammo_capacity=100,    # high-ammo rechargeable
        ammo_type="energy_cell",
        price=50,
        tech_level=1,
    ),
    GroundWeaponSpec(
        id="kinetic_pistol",
        name="Kinetic Pistol",
        damage_type="kinetic",
        damage=6,
        accuracy=72,
        ap_cost=1,
        hands=1,
        min_range=1,
        max_range=4,
        ammo_capacity=12,     # limited-ammo
        ammo_type="kinetic_pistol",
        price=35,
        tech_level=1,
    ),
    GroundWeaponSpec(
        id="smg",
        name="SMG",
        damage_type="kinetic",
        damage=5,
        accuracy=70,
        ap_cost=1,
        hands=1,
        min_range=1,
        max_range=4,
        ammo_capacity=30,
        ammo_type="kinetic_pistol",
        price=120,
        tech_level=2,
    ),
    GroundWeaponSpec(
        id="laser_carbine",
        name="Laser Carbine",
        damage_type="energy",
        damage=11,
        accuracy=76,
        ap_cost=1,
        hands=1,
        min_range=1,
        max_range=6,
        ammo_capacity=100,
        ammo_type="energy_cell",
        price=240,
        tech_level=3,
    ),
)
