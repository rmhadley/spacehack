"""Vest, helmet, and light armor pieces for ground combat.

Armour covers four slots: helmet, vest, gloves, boots.
Higher tech level = better defense.
"""

from . import GroundArmorSpec

WARES: tuple[GroundArmorSpec, ...] = (
    # --- Helmets ---
    GroundArmorSpec(
        id="light_helmet",
        name="Light Helmet",
        slot="helmet",
        defense=1,
        description="Basic impact-absorbing headgear.",
        price=25,
        tech_level=1,
    ),
    GroundArmorSpec(
        id="heavy_helmet",
        name="Heavy Helmet",
        slot="helmet",
        defense=2,
        description="Reinforced combat helmet with visor.",
        price=60,
        tech_level=2,
    ),
    # --- Vests ---
    GroundArmorSpec(
        id="light_vest",
        name="Light Armor Vest",
        slot="vest",
        defense=2,
        description="Lightweight fabric armour for mobility.",
        price=50,
        tech_level=1,
    ),
    GroundArmorSpec(
        id="medium_vest",
        name="Medium Armor Vest",
        slot="vest",
        defense=3,
        description="Plated composite vest — good all-round protection.",
        price=110,
        tech_level=2,
    ),
    GroundArmorSpec(
        id="heavy_vest",
        name="Heavy Armor Vest",
        slot="vest",
        defense=5,
        description="Full ceramic-plate carrier. Heavy but tough.",
        price=250,
        tech_level=3,
    ),
    # --- Gloves ---
    GroundArmorSpec(
        id="tactical_gloves",
        name="Tactical Gloves",
        slot="gloves",
        defense=1,
        description="Armoured knuckles and grip pads.",
        price=15,
        tech_level=1,
    ),
    # --- Boots ---
    GroundArmorSpec(
        id="combat_boots",
        name="Combat Boots",
        slot="boots",
        defense=1,
        description="Steel-toed boots with grip soles.",
        price=20,
        tech_level=1,
    ),
)
