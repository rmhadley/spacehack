"""Missile / projectile weapons.

All entries share slot_type="missile", power_cost=0 (no power needed).
Ammo is now *persistent*: rounds spent in combat stay spent until
rebought at the mechanic via ``ammo_price`` per round. ``ammo_capacity``
is the max magazine; each round uses ``cargo_per_round`` cargo space
permanently reserved.

Doc 57 (SETTLED 1-7): light and heavy missiles are FLIGHT weapons —
long-range-only (a hard floor: inside ``min_range`` the rack refuses
to fire at all), doubled damage, and a live crossing entity that flak
can shoot down (``missile_hp`` over ``flight_speed`` cells/round). The
EMP missile stays an instant pulse (``flight_speed=0``) — never
interceptible; its counters are the hard-capped magazine and its price.
"""

from . import WeaponSpec

WEAPONS: tuple[WeaponSpec, ...] = (
    WeaponSpec(
        id="light_missile", name="Light Missile", slot_type="missile",
        damage=28, accuracy=72, ap_cost=2, power_cost=0,
        ammo_capacity=4, ammo_per_shot=1, cargo_per_round=2,
        ammo_price=8, price=40, min_range=4, max_range=9,
        tech_level=1, flight_speed=4, missile_hp=2,
        grid_w=1, grid_h=2,
    ),
    WeaponSpec(
        id="heavy_missile", name="Heavy Missile", slot_type="missile",
        damage=64, accuracy=72, ap_cost=2, power_cost=0,
        ammo_capacity=3, ammo_per_shot=1, cargo_per_round=1,
        ammo_price=20, price=90, min_range=5, max_range=13,
        tech_level=3, flight_speed=2, missile_hp=6,
        grid_w=1, grid_h=2,
    ),
    WeaponSpec(
        id="emp_missile", name="EMP Missile", slot_type="missile",
        damage=0, accuracy=75, ap_cost=2, power_cost=0,
        ammo_capacity=2, ammo_per_shot=1, cargo_per_round=2,
        ammo_price=25, price=120, min_range=2, max_range=10,
        tech_level=4, shield_strip_pct=100, flight_speed=0,
        grid_w=1, grid_h=2,
    ),
)
