"""Armor pieces for ground combat — five slots: head, body, hands, legs, feet.

Higher tech level = better defense.
"""

from . import GroundArmorSpec

WARES: tuple[GroundArmorSpec, ...] = (
    # --- Head ---
    GroundArmorSpec(
        id="light_helmet",
        name="Light Helmet",
        slot="head",
        defense=1,
        description="Basic impact-absorbing headgear.",
        price=25,
        tech_level=1,
    ),
    GroundArmorSpec(
        id="heavy_helmet",
        name="Heavy Helmet",
        slot="head",
        defense=2,
        description="Reinforced combat helmet with visor.",
        price=60,
        tech_level=2,
    ),
    # --- Body ---
    GroundArmorSpec(
        id="light_vest",
        name="Light Armor Vest",
        slot="body",
        defense=2,
        description="Lightweight fabric armour for mobility.",
        price=50,
        tech_level=1,
    ),
    GroundArmorSpec(
        id="medium_vest",
        name="Medium Armor Vest",
        slot="body",
        defense=3,
        description="Plated composite vest — good all-round protection.",
        price=110,
        tech_level=2,
    ),
    GroundArmorSpec(
        id="heavy_vest",
        name="Heavy Armor Vest",
        slot="body",
        defense=5,
        description="Full ceramic-plate carrier. Heavy but tough.",
        price=250,
        tech_level=3,
    ),
    # --- Hands ---
    GroundArmorSpec(
        id="tactical_gloves",
        name="Tactical Gloves",
        slot="hands",
        defense=1,
        description="Armoured knuckles and grip pads.",
        price=15,
        tech_level=1,
    ),
    # --- Legs ---
    GroundArmorSpec(
        id="armour_pads",
        name="Armour Pads",
        slot="legs",
        defense=1,
        description="Reinforced thigh and knee pads.",
        price=25,
        tech_level=1,
    ),
    GroundArmorSpec(
        id="heavy_legs",
        name="Heavy Leg Guards",
        slot="legs",
        defense=2,
        description="Full-coverage armoured greaves.",
        price=60,
        tech_level=2,
    ),
    # --- Feet ---
    GroundArmorSpec(
        id="combat_boots",
        name="Combat Boots",
        slot="feet",
        defense=1,
        description="Steel-toed boots with grip soles.",
        price=20,
        tech_level=1,
    ),
)
