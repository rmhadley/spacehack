"""Plasma ground weapons — high-damage, infinite-ammo energy sidearms.

Plasma halves the target's armor DR (see ``combat/_rules_ground``) and
shares the ship plasma bolt animation. All entries share
``damage_type=\"plasma\"`` and ``ammo_capacity=-1`` (no ammo).
"""

from . import GroundWeaponSpec

WARES: tuple[GroundWeaponSpec, ...] = (
    GroundWeaponSpec(
        id="plasma_pistol",
        name="Plasma Pistol",
        damage_type="plasma",
        damage=9,
        accuracy=74,
        ap_cost=1,
        hands=1,
        min_range=1,
        max_range=5,
        ammo_capacity=-1,
        price=220,
        tech_level=2,
    ),
    GroundWeaponSpec(
        id="plasma_rifle",
        name="Plasma Rifle",
        damage_type="plasma",
        damage=16,
        accuracy=70,
        ap_cost=2,
        hands=2,
        min_range=1,
        max_range=8,
        ammo_capacity=-1,
        price=520,
        tech_level=3,
    ),
    GroundWeaponSpec(
        id="plasma_caster",
        name="Plasma Caster",
        damage_type="plasma",
        damage=24,
        accuracy=66,
        ap_cost=3,
        hands=2,
        min_range=1,
        max_range=7,
        ammo_capacity=-1,
        price=980,
        tech_level=4,
    ),
)
