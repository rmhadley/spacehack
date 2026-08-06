"""Monster ground weapons — enemy-only natural/machine attacks.

Never sold in armories (``shop_available=False``): the armory lists
every registered weapon, so this flag is what keeps monster attacks
out of player shops. Players can never acquire these ids.

Design doc: ``docs/design/in_progress/11_DESIGN_DUNGEON_MONSTERS.md``
"""

from . import GroundWeaponSpec

WARES: tuple[GroundWeaponSpec, ...] = (
    GroundWeaponSpec(
        id="monster_claws",
        name="Monster Claws",
        damage_type="melee",
        damage=3,
        accuracy=85,
        ap_cost=1,
        hands=1,
        min_range=1,
        max_range=1,
        ammo_capacity=-1,
        price=0,
        tech_level=1,
        shop_available=False,
    ),
    GroundWeaponSpec(
        id="drone_laser",
        name="Drone Laser",
        damage_type="energy",
        damage=4,
        accuracy=70,
        ap_cost=2,
        hands=1,
        min_range=1,
        max_range=6,
        ammo_capacity=-1,
        price=0,
        tech_level=2,
        shop_available=False,
    ),
    GroundWeaponSpec(
        id="frost_bolt",
        name="Frost Bolt",
        damage_type="energy",
        damage=4,
        accuracy=65,
        ap_cost=2,
        hands=1,
        min_range=1,
        max_range=5,
        ammo_capacity=-1,
        price=0,
        tech_level=2,
        shop_available=False,
    ),
)
