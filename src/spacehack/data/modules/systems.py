"""System modules — shields, targeting, cargo, etc.

Each entry is a ModuleSpec with slot_type="system".
"""

from . import ModuleSpec

MODULES: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        id="shield_mk1", name="Shield Mk. 1",
        slot_type="system",
        description="Basic deflector. +20 max shields.",
        max_shield_bonus=20, price=60,
    ),
    ModuleSpec(
        id="shield_capacitor", name="Shield Capacitor",
        slot_type="system",
        description="+15 max shields.",
        max_shield_bonus=15, price=80,
    ),
    ModuleSpec(
        id="shield_recharger", name="Shield Recharger",
        slot_type="system",
        description="+3 shield regen per turn.",
        shield_recharge_bonus=3, price=100,
    ),
    ModuleSpec(
        id="targeting_computer", name="Targeting Computer",
        slot_type="system",
        description="+10 gunnery.",
        gunnery_bonus=10, price=70,
    ),
    ModuleSpec(
        id="gyro_stabilizer", name="Gyro Stabilizer",
        slot_type="system",
        description="+10 piloting.",
        piloting_bonus=10, price=70,
    ),
    ModuleSpec(
        id="expanded_cargo", name="Expanded Cargo Bays",
        slot_type="system",
        description="+30 cargo capacity.",
        cargo_bonus=30, price=40,
    ),
    ModuleSpec(
        id="armor_plating", name="Armor Plating",
        slot_type="system",
        description="+5 max hull. -1 power gen.",
        max_hull_bonus=5, power_gen_bonus=-1, price=90,
    ),
)
