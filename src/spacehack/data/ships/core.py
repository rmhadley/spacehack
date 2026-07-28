"""Player ship catalog — the purchasable starships at the space port.

Extracted from ``ship.py`` during the data-first migration.
"""

from . import Ship


SHIPS: tuple[Ship, ...] = (
    Ship(
        id="scout",
        name="Scout",
        char="s",
        fg=(130, 220, 255),
        price=80,
        width=1, height=1,
        description=(
            "A small, fast scoutship - quick on cargo runs, lightly armed."
        ),
        weapon_slots=6,
        module_slots=1,
        max_cargo=40,
        max_fuel=100,
        base_power_gen=3,
        base_shield_max=0,
        base_hull=20,
    ),
    Ship(
        id="hauler",
        name="Hauler",
        char="H",
        fg=(140, 210, 140),
        price=140,
        width=2, height=1,
        description=(
            "A long-range cargo hauler with roomy cargo bays."
        ),
        weapon_slots=2,
        module_slots=2,
        max_cargo=120,
        max_fuel=80,
        base_power_gen=4,
        base_shield_max=10,
        base_hull=30,
    ),
    Ship(
        id="cruiser",
        name="Cruiser",
        char="C",
        fg=(235, 130, 130),
        price=240,
        width=2, height=2,
        description=(
            "A well-armed cruiser - capable in a fight, slow in dock."
        ),
        weapon_slots=6,
        module_slots=4,
        max_cargo=40,
        max_fuel=60,
        base_power_gen=5,
        base_shield_max=20,
        base_hull=50,
    ),
)
