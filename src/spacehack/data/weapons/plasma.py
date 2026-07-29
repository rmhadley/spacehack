"""Plasma weapons.

All entries share slot_type="plasma", ammo_capacity=-1 (no ammo).
Power cost scales with damage output.
"""

from . import WeaponSpec

WEAPONS: tuple[WeaponSpec, ...] = (
    WeaponSpec(
        id="plasma_cannon", name="Plasma Cannon", slot_type="plasma",
        damage=16, accuracy=70, ap_cost=2, power_cost=4,
        price=120, min_range=1, max_range=8,
        tech_level=3,
    ),
)
